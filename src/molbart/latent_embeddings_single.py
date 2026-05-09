import hydra
from molbart.models import Chemformer
import pickle
import torch
from molbart.data.util import BatchEncoder
import molbart.utils.data_utils as util

@hydra.main(version_base=None, config_path="config", config_name="predict")
def main(args):

    chemformer = Chemformer(args)
    chemformer.model.eval()
    
    # Prepare the single SMILES input
    single_smiles = "CCO"  # Example: Ethanol
    print(f"Processing SMILES: {single_smiles}")
    
    # Tokenize and encode the single SMILES using the BatchEncoder
    encoder = BatchEncoder(tokenizer=chemformer.tokenizer, masker=None, max_seq_len=util.DEFAULT_MAX_SEQ_LEN)

    # Encode the single SMILES without masking
    encoder_ids, encoder_mask = encoder([single_smiles], mask=False, add_sep_token=False)
    

    # Run the Chemformer model to get the encoder memory
    with torch.no_grad():
        encoder_memory = chemformer.model.encode({"encoder_input": encoder_ids, "encoder_pad_mask": encoder_mask})
        encoder_memory = encoder_memory.permute(1, 0, 2)  # Reshape to [n_samples, n_tokens, max_seq_length]
    import pdb; pdb.set_trace()
    print(encoder_memory)
    print("Finished predictions.")
    return


if __name__ == "__main__":
    main()