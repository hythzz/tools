CC=gcc
CFLAGS=-c -Wall
LDFLAGS=
DEPS=
OBJ := blkmapping.o

%.o: %.c $(DEPS)
	$(CC) $(CFLAGS) $< -o $@

all: $(OBJ)
	$(CC) $(LDFLAGS) $^ -o blkmapping

clean:
	rm -f *.o blkmapping

.PHONY: all $(%.o) 
