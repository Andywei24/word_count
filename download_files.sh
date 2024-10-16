#!/bin/bash

mkdir -p /wordCount/downloads

while IFS= read -r link
do
        echo "Downloading from $link"
        curl -L "$link" --output "/wordCount/downloads/$(basename "$link")"
done < /wordCount/links.txt
