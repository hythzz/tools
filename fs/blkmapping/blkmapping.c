#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include <linux/fiemap.h>
#include <fcntl.h>

#define FIEMAP_MAX_EXTENTS	(UINT_MAX / sizeof(struct fiemap_extent))

static void print_extent(struct fiemap_extent *extent)
{
	printf("logical: 0x%016Lx, physical: 0x%016Lx, length: 0x%016Lx\n",
		extent->fe_logical, extent->fe_physical,
		extent->fe_length);
}

int main(int argc, char **argv)
{
	long extents = 100;
	int fd, ret, print_extents = 0;
	char *end;
	struct fiemap *map;
	struct stat filestat;

	// argument parsing
	if (argc < 2 || (argc >= 3 && strcmp(argv[2], "-e") != 0)) {
		fprintf(stderr, "Usage: ./blkmapping filename [-e [max # of extents]]\n");
		return -EINVAL;
	}

	if (argc < 3 || strcmp(argv[2], "-e") != 0)
		goto openfile;

	print_extents = 1;
	if (argc == 4) {
		extents = strtol(argv[3], &end, 10);
		if (*end) {
			print_extents = 0;
			fprintf(stderr, "please enter a valid number with base 10, extent print ignored\n");
		}
	}

	if (extents > FIEMAP_MAX_EXTENTS) {
		extents = FIEMAP_MAX_EXTENTS;
		fprintf(stderr, "Warning: supplied extents count overflow, truncated to %ld\n", extents);
	}

openfile:
	// prepare and error check
	fd = open(argv[1], O_RDONLY);
	if (fd < 0) {
		fprintf(stderr, "open error: %d\n", fd);
		return fd;
	}
	
	ret = fstat(fd, &filestat);
	if (ret != 0) {
		fprintf(stderr, "fstat read error: %d\n", ret);
		goto closefile;
	}

	if (!S_ISREG(filestat.st_mode) && !S_ISDIR(filestat.st_mode)) {
		fprintf(stderr, "file is not a regular file or a directory\n");	
		goto closefile;
	}

	map = malloc(extents * sizeof(struct fiemap_extent) + sizeof(struct fiemap));
	if (map == NULL) {
		fprintf(stderr, "memory allocation for fiemap buffer failed\n");
		fprintf(stderr, "consider reduce # of extents to print\n");
		ret = -ENOMEM;
		goto closefile;
	}

	// real code to get extents information
	map->fm_start = 0;
	map->fm_length = filestat.st_size;
	map->fm_flags = FIEMAP_FLAG_SYNC;
	map->fm_extent_count = extents;
	ret = ioctl(fd, FS_IOC_FIEMAP, map);
	if (ret != 0) {
		fprintf(stderr, "ioctl read error: %d\n", ret);
		goto cleanup;
	}
	printf("filename: %s\n", argv[1]);
	printf("map extent count: %u\n", map->fm_mapped_extents);

	if (print_extents == 0)
		goto cleanup;

	for (int i = 0; i < map->fm_mapped_extents; i++){
		print_extent(&map->fm_extents[i]);
	}

cleanup:
	free(map);
closefile:
	close(fd);

	return ret;
}
