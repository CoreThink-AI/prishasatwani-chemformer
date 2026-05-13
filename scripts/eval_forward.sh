#!/usr/bin/env sh
datadir=src/chemformer/data/uspto
if [[ -n "$1" ]] ; then
    datadir="$1"
fi

modeldir=saved_models/uspto_sep/span_aug/100_epochs
if [[ -n "$2" ]] ; then
    modeldir="$2"
fi

python -m molbart.inference_score \
  data_path="$datadir"/uspto_sep.pickle \
  model_path="$modeldir"/last.ckpt \
  vocabulary_path=bart_vocab_downstream.json \
  datamodule=[molbart.data.seq2seq_data.UsptoSepDataModule] \
  task=forward_prediction \
  model_type=bart \
  batch_size=64 \
  n_beams=10
