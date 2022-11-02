#!/bin/sh -l

ls -la

file = /data/test/input.txt
awk '{ sum += $file } END { print sum }' file >> sum
echo "summe=$sum" >> $GITHUB_OUTPUT
