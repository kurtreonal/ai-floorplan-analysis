import cv2
import numpy as np
from app.ai.wall_detection.paired_boundaries import recover_paired_boundaries


def scene():
    image=np.full((500,500,3),255,np.uint8)
    cv2.line(image,(40,60),(460,60),(90,70,110),12)
    seed=[(40,60,460,60,12)]
    return image,seed,np.full((500,500),255,np.uint8)


def partition(image,x=240,end=440):
    for edge in (x-5,x+5):cv2.line(image,(edge,60),(edge,end),(0,0,0),2)


def test_recovers_anchored_outlined_partition_without_single_grid_or_wire():
    image,seeds,scope=scene();partition(image)
    for x in (100,150,350,400):cv2.line(image,(x,100),(x,440),(0,0,0),1)
    cv2.line(image,(20,180),(470,180),(0,0,0),1)
    rows=recover_paired_boundaries(image,seeds,scope)
    assert rows and all(abs((r[0]+r[2])/2-240)<2 for r in rows)
    assert max(max(r[1],r[3]) for r in rows)>=438
    assert recover_paired_boundaries(image,seeds,scope)==rows


def test_door_gap_is_not_closed_and_floating_fixture_is_not_a_partition():
    image,seeds,scope=scene();partition(image)
    image[250:285,230:251]=255
    cv2.rectangle(image,(340,150),(350,360),(0,0,0),2)
    rows=recover_paired_boundaries(image,seeds,scope)
    assert rows
    assert all(not(min(r[1],r[3])<250 and max(r[1],r[3])>285) for r in rows)
    assert all(abs((r[0]+r[2])/2-345)>3 for r in rows)


def test_window_inner_rails_are_not_recovered_as_solid_wall():
    image,seeds,scope=scene();partition(image)
    cv2.line(image,(240,62),(240,440),(0,0,0),1)
    assert not recover_paired_boundaries(image,seeds,scope)


def test_nearby_distinct_partitions_and_rotated_source_survive():
    image,seeds,scope=scene();partition(image,220);partition(image,245)
    rows=recover_paired_boundaries(image,seeds,scope)
    assert any(abs((r[0]+r[2])/2-220)<2 for r in rows)
    assert any(abs((r[0]+r[2])/2-245)<2 for r in rows)
    rotated=cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE)
    other=[(439,40,439,460,12)]
    rows=recover_paired_boundaries(rotated,other,scope)
    assert rows and all(abs(r[3]-r[1])<2 for r in rows)
