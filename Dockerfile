# Use an official Python runtime as a parent image
FROM python:3.7-slim

RUN apt-get update 
RUN apt-get install libavdevice-dev libavfilter-dev libopus-dev libvpx-dev pkg-config -y
RUN apt-get install gcc -y


# Set the working directory to /
#WORKDIR /

# Copy the current directory contents into the container at /hyperpeer
ADD ./hyperpeer /hyperpeer
COPY requirements.txt  hp-requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r hp-requirements.txt

#EXPOSE 8080

CMD python 
#ENTRYPOINT exec python -m unittest -v /test/test.py