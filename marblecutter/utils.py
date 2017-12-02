# coding=utf-8
from collections import namedtuple

Bounds = namedtuple('Bounds', ['bounds', 'crs'])
PixelCollection = namedtuple('PixelCollection', ['data', 'bounds', 'band'])
PixelCollection.__new__.__defaults__ = (None, )
Source = namedtuple('Source',
                    ['url', 'name', 'resolution', 'band', 'meta', 'recipes'])