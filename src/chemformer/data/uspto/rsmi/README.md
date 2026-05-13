From Schwaller paper https://pubs.rsc.org/en/content/articlepdf/2018/sc/c8sc02339e and CSV files https://figshare.com/articles/dataset/Yield_curation_USPTO_rsmi_csv_datasets/14414039

CSV files are TAB-separated so they should be renamed *.TSV after unzipping as was done for Lowe*.zip.

```bash
unzip Lowe_USPTOapplications_smiles_yield_ok_all_data.zip
# mv 1976_Sep2016_USPTOgrants_smiles_yield_ok_all_data.csv 1976_Sep2016_USPTOgrants_smiles_yield_ok_all_data.csv.tsv
for filepath in *.csv; do
    echo mv "$filepath" "$(basename "$filepath" .).tsv"
    mv "$filepath" "$(basename "$filepath" .).tsv"
done
```

#### `head 1976_Sep2016_USPTOgrants_smiles_yield_ok_all_data.tsv `
```
	myID	ReactionSmiles	PatentNumber	ParagraphNum	Year	TextMinedYield	CalculatedYield	Yield
0	ID00000000	[Br:1][CH2:2][CH2:3][OH:4].[CH2:5]([S:7](Cl)(=[O:9])=[O:8])[CH3:6].CCOCC>C(N(CC)CC)C>[CH2:5]([S:7]([O:4][CH2:3][CH2:2][Br:1])(=[O:9])=[O:8])[CH3:6]	US03930836	1976			0.0
1	ID00000001	[Br:1][CH2:2][CH2:3][CH2:4][OH:5].[CH3:6][S:7](Cl)(=[O:9])=[O:8].CCOCC>C(N(CC)CC)C>[CH3:6][S:7]([O:5][CH2:4][CH2:3][CH2:2][Br:1])(=[O:9])=[O:8]	US03930836		1976			0.0
2	ID00000002	[CH2:1]([Cl:4])[CH2:2][OH:3].CCOCC.[CH2:10]([S:14](Cl)(=[O:16])=[O:15])[CH:11]([CH3:13])[CH3:12]>C(N(CC)CC)C>[CH2:10]([S:14]([O:3][CH2:2][CH2:1][Cl:4])(=[O:16])=[O:15])[CH:11]([CH3:13])[CH3:12]	US03930836		1976			0.0
3	ID00000003	[Br:1][CH2:2][CH2:3][OH:4].[CH2:5]([S:7](Cl)(=[O:9])=[O:8])[CH3:6].CCOCC>C(N(CC)CC)C>[CH2:5]([S:7]([O:4][CH2:3][CH2:2][Br:1])(=[O:9])=[O:8])[CH3:6]	US03930839	1976			0.0
4	ID00000004	[Br:1][CH2:2][CH2:3][CH2:4][OH:5].[CH3:6][S:7](Cl)(=[O:9])=[O:8].CCOCC>C(N(CC)CC)C>[CH3:6][S:7]([O:5][CH2:4][CH2:3][CH2:2][Br:1])(=[O:9])=[O:8]	US03930839		1976			0.0
5	ID00000005	[CH2:1]([Cl:4])[CH2:2][OH:3].CCOCC.[CH2:10]([S:14](Cl)(=[O:16])=[O:15])[CH:11]([CH3:13])[CH3:12]>C(N(CC)CC)C>[CH2:10]([S:14]([O:3][CH2:2][CH2:1][Cl:4])(=[O:16])=[O:15])[CH:11]([CH3:13])[CH3:12]	US03930839		1976			0.0
6	ID00000006	[Cl:1][C:2]1[N:3]=[CH:4][C:5]2[C:10]([CH:11]=1)=[C:9]([N+:12]([O-])=O)[CH:8]=[CH:7][CH:6]=2.O.[OH-].[Na+]>C(O)(=O)C.[Fe]>[Cl:1][C:2]1[N:3]=[CH:4][C:5]2[C:10]([CH:11]=1)=[C:9]([NH2:12])[CH:8]=[CH:7][CH:6]=2 |f:2.3|	US03930837		1976			0.0
7	ID00000007	[CH3:1][C:2]1[N+:3]([O-])=[CH:4][C:5]2[C:10]([CH:11]=1)=[C:9]([N+:12]([O-:14])=[O:13])[CH:8]=[CH:7][CH:6]=2.P(Cl)(Cl)([Cl:18])=O>>[Cl:18][C:4]1[C:5]2[C:10](=[C:9]([N+:12]([O-:14])=[O:13])[CH:8]=[CH:7][CH:6]=2)[CH:11]=[C:2]([CH3:1])[N:3]=1	US03930837		1976			0.0
8	ID00000008	[CH3:1][C:2]1[N:3]=[CH:4][C:5]2[C:10]([CH:11]=1)=[C:9]([N+:12]([O-:14])=[O:13])[CH:8]=[CH:7][CH:6]=2.[ClH:15]>>[ClH:15].[CH3:1][C:2]1[N:3]=[CH:4][C:5]2[C:10]([CH:11]=1)=[C:9]([N+:12]([O-:14])=[O:13])[CH:8]=[CH:7][CH:6]=2 |f:2.3|	US03930837		1976			0.0
```


