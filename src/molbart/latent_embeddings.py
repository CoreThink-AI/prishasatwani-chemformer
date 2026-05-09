import hydra
from molbart.models import Chemformer
import pickle
import torch

@hydra.main(version_base=None, config_path="config", config_name="predict")
def main(args):

    chemformer = Chemformer(args)
    
    print("Encoding dataset...")
    encoder_memory = chemformer.encode(dataset=args.dataset_part) # is of shape [n_samples, n_tokens, max_seq_length]
    print(f"Encoding complete. Total sequences encoded: {len(encoder_memory)}")

    torch.save(encoder_memory, "chemformer_encoder_memory.pt")
    
    return


if __name__ == "__main__":
    main()
    
