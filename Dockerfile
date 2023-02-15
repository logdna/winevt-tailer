FROM ubuntu:focal
ARG USER_ID=5000
ARG GROUP_ID=5000
USER root
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install -y wget software-properties-common gnupg2 winbind xvfb
RUN dpkg --add-architecture i386
RUN wget -nc https://dl.winehq.org/wine-builds/winehq.key
RUN apt-key add winehq.key
RUN add-apt-repository 'deb https://dl.winehq.org/wine-builds/ubuntu/ focal main'
RUN apt-get update
RUN apt-get install -y winehq-stable
RUN apt-get install -y winetricks
RUN apt-get clean -y
RUN apt-get autoremove -y
ENV WINEDEBUG=-all
ENV WINEPREFIX=/home/logdna/.wine
ENV DISPLAY=
RUN groupadd -g $GROUP_ID logdna && useradd -m -u $USER_ID -g logdna logdna
USER logdna
WORKDIR /home/logdna
RUN mkdir -p ./workdir && chmod 777 ./workdir
RUN wineboot -u
RUN winetricks cmd
RUN winetricks win10
ARG MINICONDA_INSTALL=Miniconda3-py310_23.1.0-1-Windows-x86_64.exe
RUN wget -q https://repo.anaconda.com/miniconda/$MINICONDA_INSTALL && \
    xvfb-run wine ./$MINICONDA_INSTALL /InstallationType=JustMe /RegisterPython=1 /S /D=%UserProfile%\\Miniconda3 && \
    rm $MINICONDA_INSTALL
RUN rm Miniconda3-py310_23.1.0-1-Windows-x86_64.exe
ENV WINEPATH=C:\\users\\logdna\\miniconda3\\condabin;C:\\users\\logdna\\miniconda3\\Scripts;C:\\users\\logdna\\miniconda3\\Library\\bin;C:\\users\\logdna\\miniconda3\\Library\\usr\\bin
RUN wine cmd /C conda.bat init cmd.exe
RUN wine cmd /C conda.bat install pip git make -c conda-forge
RUN wine cmd /C pip.exe install poetry
RUN wine cmd /C git.exe config --global --add safe.directory ./workdir
WORKDIR /home/logdna/workdir
