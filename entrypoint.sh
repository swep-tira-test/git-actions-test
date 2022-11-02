#!/bin/bash

file=./input.txt

sum=0
while read -r line
do
   (( sum += line ))
done < $file
echo $sum

echo "summe=$sum" >> $GITHUB_OUTPUT
