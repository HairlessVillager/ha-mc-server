ARG BASE_IMAGE
FROM ${BASE_IMAGE}

WORKDIR /mc

RUN java -version
RUN mkdir save

ARG SPIGOT_FILE
COPY ./${SPIGOT_FILE} .

COPY ./server.properties .

ARG EULA
RUN echo eula=${EULA} > eula.txt

CMD ["/bin/sh"]
