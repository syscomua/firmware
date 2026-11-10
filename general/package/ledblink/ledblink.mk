################################################################################
#
# ledblink
#
################################################################################

LEDBLINK_SITE_METHOD = local
LEDBLINK_SITE = $(LEDBLINK_PKGDIR)/src

LEDBLINK_LICENSE = MIT

define LEDBLINK_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) -std=gnu99 $(@D)/ledblink.c -o $(@D)/ledblink -lrt -s
endef

define LEDBLINK_INSTALL_TARGET_CMDS
	$(INSTALL) -m 0755 -t $(TARGET_DIR)/usr/bin $(@D)/ledblink
endef

$(eval $(generic-package))
