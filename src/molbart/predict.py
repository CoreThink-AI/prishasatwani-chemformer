from pathlib import Path

import omegaconf as oc
import pandas as pd

from molbart.constants import CONFIG_DIR
from molbart.models import Chemformer


def write_predictions(args, smiles, log_lhs, original_smiles):
    num_data = len(smiles)
    beam_width = len(smiles[0])
    beam_outputs = [[[]] * num_data for _ in range(beam_width)]
    beam_log_lhs = [[[]] * num_data for _ in range(beam_width)]

    for b_idx, (smiles_beams, log_lhs_beams) in enumerate(zip(smiles, log_lhs)):
        for beam_idx, (smi, log_lhs) in enumerate(zip(smiles_beams, log_lhs_beams)):
            beam_outputs[beam_idx][b_idx] = smi
            beam_log_lhs[beam_idx][b_idx] = log_lhs

    df_data = {"target_smiles": original_smiles}
    for beam_idx in range(beam_width):
        df_data["sampled_smiles_" + str(beam_idx + 1)] = beam_outputs[beam_idx]

    for beam_idx in range(beam_width):
        df_data["loglikelihood_" + str(beam_idx + 1)] = beam_log_lhs[beam_idx]

    df = pd.DataFrame(data=df_data)
    df.to_csv(args.output_sampled_smiles, sep="\t", index=False)


# @hydra.main(version_base=None, config_path=Path(CONFIG_DIR) / "predict.yaml"))
def predict_reaction(config_path=Path(CONFIG_DIR) / "predict.yaml", batch_size=None, n_beams=10, task="backward_prediction", **kwargs):
    """ Predict the retrosynthesis SMARTS (reactants) from product SMILES """
    config = oc.OmegaConf.load(config_path)
    config.n_beams = config.n_beams if n_beams is None else n_beams
    config.batch_size = config.batch_size if batch_size is None else batch_size
    config.task = config.task if task is None else task
    for k in kwargs:
        assert hasattr(config, k), f"Config file {config_path} does not have attribute {k}."
        setattr(config, k, kwargs[k])
    # model_path = os.environ["CHEMFORMER_DISCONNECTION_MODEL"]
    # model_type = "bart"
    # config.n_unique_beams = 10 # Make sure we output unique predictions
    # config.vocabulary_path = os.environ["CHEMFORMER_VOCAB"]
    # config.datamodule = None
    chemformer = Chemformer(config)

    print(f"Making task={config.task} predictions on dataset_part={config.dataset_part} using model={config.model_path}...")
    smiles, log_lhs, original_smiles = chemformer.predict(
        dataset=config.dataset_part,  # full, test, val, train
    )
    prediction = dict(smiles=smiles, log_lhs=log_lhs, original_smiles=original_smiles, config=config)
    write_predictions(**prediction)
    return prediction


if __name__ == "__main__":
    predict_reaction()
