#!/bin/bash
#-v $PWD/hyperpeer:/hyperpeer 
docker run --name hyperpeer-py-test -v $PWD/test:/test -it --rm hyperpeer-py-test