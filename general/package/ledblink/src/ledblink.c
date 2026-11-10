/*
 * ledblink - blink an LED on a GPIO pin with a fixed frequency and
 * skip a number of full periods every second.
 *
 * Default pattern (50 Hz, skip 2):
 *   one period  = 20 ms (10 ms ON + 10 ms OFF)
 *   one second  = 50 periods = 48 blinks + 2 skipped periods (40 ms OFF)
 *
 *   |_|‾|_|‾|_| ... |‾|_|_____|‾|_|‾| ...
 *    \__ 48 blinks __/\ 40ms /\_ next second
 *
 * Timing is drift-free: every edge is scheduled at an absolute time
 * (CLOCK_MONOTONIC) relative to the start of the current second.
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#ifndef GPIO_SYSFS
#define GPIO_SYSFS "/sys/class/gpio"
#endif

#define NSEC_PER_SEC 1000000000LL

static volatile sig_atomic_t running = 1;

static void on_signal(int sig) {
	(void)sig;
	running = 0;
}

static int write_file(const char *path, const char *val) {
	int fd = open(path, O_WRONLY);
	if (fd < 0)
		return -1;

	ssize_t len = (ssize_t)strlen(val);
	ssize_t ret = write(fd, val, len);
	close(fd);

	return ret == len ? 0 : -1;
}

static int gpio_open(int gpio, int *exported) {
	char path[128], num[16];
	struct stat st;

	*exported = 0;
	snprintf(path, sizeof(path), GPIO_SYSFS "/gpio%d", gpio);
	if (stat(path, &st) != 0) {
		snprintf(num, sizeof(num), "%d", gpio);
		if (write_file(GPIO_SYSFS "/export", num) != 0) {
			fprintf(stderr, "Cannot export GPIO-%d: %s\n", gpio, strerror(errno));
			return -1;
		}
		*exported = 1;
	}

	snprintf(path, sizeof(path), GPIO_SYSFS "/gpio%d/direction", gpio);
	if (write_file(path, "out") != 0) {
		fprintf(stderr, "Cannot set GPIO-%d direction: %s\n", gpio, strerror(errno));
		return -1;
	}

	snprintf(path, sizeof(path), GPIO_SYSFS "/gpio%d/value", gpio);
	int fd = open(path, O_WRONLY);
	if (fd < 0)
		fprintf(stderr, "Cannot open %s: %s\n", path, strerror(errno));

	return fd;
}

static void gpio_unexport(int gpio) {
	char num[16];

	snprintf(num, sizeof(num), "%d", gpio);
	write_file(GPIO_SYSFS "/unexport", num);
}

static inline void led_set(int fd, int on, int invert) {
	const char *val = (on ^ invert) ? "1" : "0";

	if (pwrite(fd, val, 1, 0) != 1)
		perror("write");
}

static void ts_add(struct timespec *ts, long long ns) {
	ns += ts->tv_nsec;
	ts->tv_sec += ns / NSEC_PER_SEC;
	ts->tv_nsec = ns % NSEC_PER_SEC;
}

static void usage(const char *name) {
	printf("Usage: %s -g <gpio> [options]\n"
		"  -g <num>   GPIO pin number (required)\n"
		"  -f <hz>    Blink frequency, default 50\n"
		"  -s <num>   Full periods to skip every second, default 2\n"
		"  -i         Invert output (LED is active LOW)\n"
		"  -r         Use realtime scheduling (lower jitter)\n"
		"  -h         Show this help\n", name);
}

int main(int argc, char **argv) {
	int gpio = -1, freq = 50, skip = 2, invert = 0, realtime = 0, opt;

	while ((opt = getopt(argc, argv, "g:f:s:irh")) != -1) {
		switch (opt) {
		case 'g':
			gpio = atoi(optarg);
			break;
		case 'f':
			freq = atoi(optarg);
			break;
		case 's':
			skip = atoi(optarg);
			break;
		case 'i':
			invert = 1;
			break;
		case 'r':
			realtime = 1;
			break;
		default:
			usage(argv[0]);
			return opt == 'h' ? 0 : 1;
		}
	}

	if (gpio < 0 || freq < 1 || freq > 1000 || skip < 0 || skip > freq) {
		usage(argv[0]);
		return 1;
	}

	struct sigaction sa;
	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = on_signal;
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);

	if (realtime) {
		struct sched_param sp = { .sched_priority = sched_get_priority_max(SCHED_FIFO) };
		if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0)
			perror("sched_setscheduler");
		if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0)
			perror("mlockall");
	}

	int exported;
	int fd = gpio_open(gpio, &exported);
	if (fd < 0)
		return 1;

	/* Two edges (ON and OFF) per period */
	const int edges = freq * 2;
	const int active = (freq - skip) * 2;

	printf("GPIO-%d: %d Hz, %d blinks + %d skipped periods per second\n",
		gpio, freq, freq - skip, skip);

	struct timespec second, next;
	clock_gettime(CLOCK_MONOTONIC, &second);

	while (running) {
		for (int i = 0; i < edges && running; i++) {
			/* Even edge = LED ON, odd edge = LED OFF.
			 * The last active edge is OFF, so the LED stays dark
			 * during the skipped periods at the end of the second. */
			if (i < active)
				led_set(fd, !(i & 1), invert);

			/* Absolute time of the next edge, computed from the start
			 * of the second to avoid accumulating rounding errors */
			next = second;
			ts_add(&next, (long long)(i + 1) * NSEC_PER_SEC / edges);
			while (running && clock_nanosleep(CLOCK_MONOTONIC,
				TIMER_ABSTIME, &next, NULL) == EINTR);
		}

		ts_add(&second, NSEC_PER_SEC);
	}

	led_set(fd, 0, invert);
	close(fd);

	if (exported)
		gpio_unexport(gpio);

	return 0;
}
