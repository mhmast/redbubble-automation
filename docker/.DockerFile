FROM budtmo/docker-android:emulator_11.0


#Set Env
ENV LC_ALL C.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

USER root

#Install Frida
RUN apt-get install -y python3 python3-pip
#Install Frida CLI tools
RUN pip install frida-tools

RUN pip3 install colorama prompt-toolkit pygments tqdm requests
#Install Frida bindings
# RUN pip3 install frida

RUN usermod -aG sudo androidusr

ENV EMULATOR_ADDITIONAL_ARGS "-no-snapshot-load -no-snapshot"
# COPY frida-server-16.6.1-android-x86_64 /tmp/local/frida-server
COPY android-11 /home/androidusr/android-11
COPY F-for-Frida.py /tmp/local/F-for-Frida.py
COPY frida-android-repinning_sa-1.js /tmp/local/frida-android-repinning_sa-1.js
COPY startup.sh /home/androidusr/docker-android/mixins/scripts/startup.sh
#COPY gsi_gms_x86_64-exp-BP11.241121.013-12873528-73684867.zip /tmp/image.zip
#RUN unzip /tmp/image.zip -d /opt/android/system-images/android-30/google_apis/x86-x64
#RUN rm /tmp/image.zip

USER androidusr

ENTRYPOINT ["/home/androidusr/docker-android/mixins/scripts/startup.sh"]