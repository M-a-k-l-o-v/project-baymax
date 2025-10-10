#include <stdio.h>
int main(int argc, char* argv[])
{
    /*printf("You have entered %d arguments:\n", argc);*/

    char* filename[argc];
    for (int i = 1; i < argc; i++) {
        int j = i-1;
        filename[j] = argv[i];
        /*printf("%s\n", argv[i]);*/
    }
    filename[argc] = NULL;
    printf("the command was - find ~/Downloads -name %s", filename);
    execv("find ~/Downloads -name", filename);
    
    return 0;
}