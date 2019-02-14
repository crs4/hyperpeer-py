#!/bin/bash
docker run --name hyperpeer-py-test -v $PWD/hyperpeer:/hyperpeer -v $PWD/test:/test -it --rm hyperpeer-py-test