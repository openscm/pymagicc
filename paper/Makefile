all: paper.pdf

paper.pdf: paper.md paper.bib
	pandoc --filter pandoc-citeproc --bibliography paper.bib  paper.md \
  --template latex.template -o paper.pdf

clean:
	rm paper.pdf

.PHONY: clean
