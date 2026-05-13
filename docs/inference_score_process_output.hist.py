import json
uspto260 = open('outputs/inference_score_uspto_260_output_sampled_smiles.json')
uspto260 = json.load(uspto260)
uspto260
uspto260.keys()
uspto260['schema'].keys()
uspto260['schema']['fields'].keys()
uspto260['schema']['fields']
type(uspto260['data'])
type(uspto260['data'][0])
uspto260['data'][0].keys()
import pandas as pd
df = pd.read_csv(uspto260['data'])
df = pd.read_csv(dict(list(enumerate(uspto260['data']))))
df = pd.DataFrame(dict(list(enumerate(uspto260['data']))))
df
df = df.T
df2 = pd.DataFrame(uspto260['data'])
df2
df2 = pd.DataFrame(uspto260['data'], index='index')
df2 = pd.DataFrame(uspto260['data'], indexcol='index')
df2 = pd.DataFrame(uspto260['data'], index_col='index')
df = pd.DataFrame(uspto260['data'])
df.set_index('index')
df.set_index('index').iloc[0]
df.set_index('index').iloc[0].T
df.set_index('index').iloc[0].to_dict()
df3 = pd.DataFrame(json.load(open('outputs/inference_score_uspto_260_output_sampled_smiles.json'))['data'])
len(df3)
df3 = pd.DataFrame(json.load(open('outputs/inference_score_uspto_260_output_sampled_smiles.json'))['data']).T
len(df3)
df3
df2
len(uspto260['data'])
len(uspto260['data'][0])
df3 = pd.DataFrame(json.load(open('outputs/inference_score_uspto_260_output_sampled_smiles.json'))['data'])
df3
df3 = df3.set_index('index')
df3 = pd.DataFrame(json.load(open('outputs/inference_score_uspto_260_output_sampled_smiles.json'))['data']).set_index('index')
df2
df3['sampled_molecules'].str.len()
df3['target_smiles'].str.len()
df3['target_smiles'].str[0]
for i in range(4):
    df3[f'sampled_molecules{i}'] = df3['sampled_molecules'].str[i]
    df3[f'target_smiles{i}'] = df3['target_smiles'].str[i]
df3.T
df3.iloc.T
df3.iloc[0].T
for i in range(4):
    for j in range(10):
        df3[f'sampled_molecules_{i}_{j}'] = df3[f'sampled_molecules{i}'].str[j]
df3['sampled_molecules0'].str.len()
hist -o -p -f docs/inference_score_process_output.hist.ipy
hist -f docs/inference_score_process_output.hist.py
