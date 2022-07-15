# -*- coding: UTF-8 -*-

VERSION = '0.2.5'

def getBit(pByte, pIndex):
    return (pByte >> pIndex) & 0x01


def getBits(pBytes, pIndex, pStartIndex, pEndIndex):
    if pStartIndex > pEndIndex: 
        StartIndex = pEndIndex
        EndIndex = pStartIndex
    else:
        StartIndex = pStartIndex
        EndIndex = pEndIndex
    tempVal = 0x00;
    i = StartIndex
    while (i <= EndIndex):
        tempVal = tempVal | getBit(pBytes[pIndex],i) << (i-StartIndex)
        i += 1 
    return tempVal