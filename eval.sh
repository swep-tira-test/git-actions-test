#!/bin/bash

RESULT=$ENV_RESULT

CORRECT_RESULT=151

if [[ "$CORRECT_RESULT" -eq $RESULT ]] ; then
echo "correct!"
else
echo "incorrect!"
fi
