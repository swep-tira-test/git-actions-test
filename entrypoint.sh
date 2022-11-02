#!/bin/sh -l

file=./input.txt

cat $file

sum=0
while read -r line
do
   (( sum += line ))
done < $file
echo $sum

echo "summe=$sum" >> $GITHUB_OUTPUT
