SRCS := $(wildcard *.pdoc)
HTML := $(SRCS:.pdoc=.html)

all: $(HTML)

%.html: %.pdoc
	uv run picodoc $< -o $@

clean:
	rm -f $(HTML)

.PHONY: all clean
