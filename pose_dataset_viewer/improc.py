import functools

import cv2
import jpeg4py
import numpy as np


def decode_jpeg(jpeg_bytes):
    return jpeg4py.JPEG(np.frombuffer(jpeg_bytes, np.uint8)).decode()


def draw_mask(img, mask, mask_color):
    outline = get_inline(mask > 0, 1, 5)
    imcolor = img[mask > 0].astype(np.float64)
    img[mask > 0] = np.clip(mask_color * 0.3 + imcolor * 0.7, 0, 255).astype(np.uint8)
    img[outline] = mask_color


def erode(mask, kernel_size, iterations=1):
    if kernel_size == 1:
        return mask
    elem = get_structuring_element(cv2.MORPH_ELLIPSE, kernel_size)
    return cv2.morphologyEx(mask, cv2.MORPH_ERODE, elem, iterations=iterations)


def get_inline(mask, d1=1, d2=3):
    if mask.dtype == np.bool:
        return get_inline(mask.astype(np.uint8), d1, d2).astype(np.bool)
    return erode(mask, d1) - erode(mask, d2)


@functools.lru_cache()
def get_structuring_element(shape, ksize, anchor=None):
    if not isinstance(ksize, tuple):
        ksize = (ksize, ksize)
    return cv2.getStructuringElement(shape, ksize, anchor)
