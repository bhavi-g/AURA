.PHONY: eval
eval:
	python evaluation/run_eval.py --golden data/sample/golden.json --out evaluation/results.json && \
	python evaluation/gate.py --results evaluation/results.json --f1 0.75 --ece 0.05
