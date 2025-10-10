#include <stdio.h>
#include <unistd.h>

int main(){

    char* file[] = {"bank statement",NULL};
    printf("the command was - ./pathfinder %s", file);
    execv("./pathfinder", file);
}
