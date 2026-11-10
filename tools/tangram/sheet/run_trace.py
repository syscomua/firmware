import sys, math, json
import numpy as np, cv2
from trace import *
PHOTO='/root/.claude/uploads/746e9745-5d65-5192-98ab-5449622e39de/eaddfa52-image.jpg'
im=load(PHOTO)
def trace_cell(r,c,half=62):
    g=cell_image(im,r,c,half)
    keep,cs,hier=contours(g)
    A=(keep>0).sum()
    u=math.sqrt(A/8) if A else 1
    parts=[]
    for i,cnt in enumerate(cs):
        if cv2.contourArea(cnt)<150: continue
        hole = hier[0][i][3]!=-1
        pts=simplify(cnt)
        opts=snap_polygon(pts,u)
        parts.append((hole,pts,opts))
    return u,parts
if __name__=='__main__':
  for r in range(8):
    for c in range(6):
      u,parts=trace_cell(r,c)
      desc=[]
      for hole,pts,opts in parts:
          ars=sorted({round(area(to_points(s)),3) for s,_ in opts})
          desc.append(('H' if hole else 'P', len(pts), ars[:8]))
      print((r,c),'u=%.1f'%u,desc)
