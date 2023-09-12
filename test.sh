#!/bin/bash
#-v $PWD/hyperpeer:/hyperpeer 
docker run --name hyperpeer-py-test -v $PWD/test:/hyperpeer/test -it -P --rm harbor.crs4.it/riale/hyperpeer-py:latest