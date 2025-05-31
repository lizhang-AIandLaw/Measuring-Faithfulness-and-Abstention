#!/bin/bash

models=(
    "qwen-qwq-32b"
)

files=(
    "reordered_factor_3_complexity4.csv"
)

for model in "${models[@]}"; do
    for file in "${files[@]}"; do
        echo "Running with model: $model and file: $file"
        python pipeline.py --model="$model" --input-file "$file"
    done
done


