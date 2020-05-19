#!/bin/bash
#-v $PWD/hyperpeer:/hyperpeer 
docker run --name hyperpeer-py-test -v $PWD/test:/test -it -P --rm 156.148.14.162/hyperpeer-py:latest