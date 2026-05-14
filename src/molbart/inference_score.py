import json
from pathlib import Path

import hydra
import omegaconf as oc
import pandas as pd

import molbart.utils.data_utils as util
from molbart.constants import MODELS_DIR
from molbart.models import Chemformer


def load_output(output_path):
    """ See src/molbart/config/inference_score.yaml for test dataset data_path """
    df = pd.DataFrame(json.load(open(output_path))['data']).set_index('index')
    for i in range(4):
        df[f'sampled_molecules_{i}'] = df['sampled_molecules'].str[i]
        for j in range(10):
            df[f'sampled_molecules_{i}_{j}'] = df['sampled_molecules'].str[i].str[j]
        df[f'target_smiles_{i}'] = df['target_smiles'].str[i]
    return df
    # for i in range(4):
    #     df3.to_csv('docs/inference_score_uspto_260_output.csv')


# @hydra.main(version_base=None, config_path=CONFIG_DIR, config_name="inference_score")
def main(cfg, chemformer):
    chemformer.score_model(
        n_unique_beams=cfg.n_unique_beams,
        dataset=cfg.dataset_part,
        output_scores=cfg.output_score_data,
        output_sampled_smiles=cfg.output_sampled_smiles,
    )
    print("Model inference and scoring done.")
    return chemformer


if __name__ == "__main__":
    with hydra.initialize(version_base=None, config_path='config', job_name="hobs_attempting_run_inference_score"):
        cfg = hydra.compose(config_name="inference_score")  # "fine_tune")
        print(f'cfg.data_path from inference_score.yaml: {cfg.data_path}')
    util.seed_everything(cfg.seed)

    smiles_dataset = pd.read_csv(cfg.data_path, sep='\t')
    smiles = smiles_dataset['reactants'].values.tolist()
    print(f"Finished reading {len(smiles)} smiles from data_path={cfg.data_path} ['reactants'].")
    extra_tokens_cfg_name = f"{Path(cfg.data_path).with_suffix('').name}_tokens_path"
    print(f'extra_tokens_cfg_name={extra_tokens_cfg_name}')
    # cfg.data_path = cfg.data_path or str(Path(DATA_DIR) / 'seq-to-seq_datasets' / 'uspto_1.tsv')
    cfg.model_path = str(Path(MODELS_DIR) / 'pre-trained' / 'combined-large' / 'step=1000000.ckpt')
    cfg.vocabulary_path = str(Path(cfg.model_path).parent / 'bart_vocab.json')
    print('cfg.data_path (inference_score.yaml) in inference_score.py:')
    print(f'               cfg.seed: {cfg.seed}')
    print(f'         cfg.batch_size: {cfg.batch_size}')
    print(f'          cfg.data_path: {cfg.data_path}')
    print(f'         cfg.model_path: {cfg.model_path}')
    print(f'    cfg.vocabulary_path: {cfg.vocabulary_path}')
    cfg.n_gpus = 0


    print(f'Loading Chemformer model with cfg:\n{cfg}')
    chemformer = Chemformer(cfg)

    # BAD IDEA!!!
    # print('Trying to update tokenizer vocab...')
    # tokenizer = chemformer.tokenizer.create_vocabulary_from_smiles(smiles)
    # print(f'New tokenizer: {chemformer.tokenizer}')
    # print(f'New chemformer: {chemformer}')
    # cfg.vocabulary_path = str(Path(MODELS_DIR) / 'pre-trained' / 'combined-large' / 'tokenizer_vocab.json')

    print(oc.OmegaConf.to_yaml(cfg))

    print("Running model inference and scoring...")

    chemformer = main(cfg, chemformer=chemformer)
