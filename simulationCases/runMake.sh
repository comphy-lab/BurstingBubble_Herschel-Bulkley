#!/bin/bash

source ../.project_config
echo $BASILISK

mkdir -p $1

qcc -O2 -Wall -disable-dimensions -I$(PWD)/src-local -I$(PWD)/../src-local $1.c -o $1/$1 -lm 
cd $1
./$1