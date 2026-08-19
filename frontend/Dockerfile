FROM nginx:alpine

RUN apk add --no-cache iputils curl bind-tools

COPY index.html /usr/share/nginx/html/index.html
COPY about.html /usr/share/nginx/html/about.html
COPY services.html /usr/share/nginx/html/services.html
COPY contact.html /usr/share/nginx/html/contact.html
COPY blog.html /usr/share/nginx/html/blog.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
