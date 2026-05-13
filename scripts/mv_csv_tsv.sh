#!/usr/bin/env sh

# mv 1976_Sep2016_USPTOgrants_smiles_yield_ok_all_data.csv 1976_Sep2016_USPTOgrants_smiles_yield_ok_all_data.csv.tsv
datadir=$1
cd datadir
for filepath in *.csv; do
    echo mv "$filepath" "$(basename "$filepath" .).tsv"
    mv "$filepath" "$(basename "$filepath" .).tsv"
done
