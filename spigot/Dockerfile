ARG BASE_IMAGE
FROM ${BASE_IMAGE}

WORKDIR /mc

RUN java -version
RUN mkdir save
COPY ./server.properties .

ARG EULA
RUN echo eula=${EULA} > eula.txt

ARG SPIGOT_FILE
COPY ./${SPIGOT_FILE} .

CMD ["/bin/sh"]
