# Get it running

```
cp .env.example .env
docker build -t my-proof .
docker run --rm --net=host --volume ./input:/input --volume ./output:/output --env-file .env my-proof
```
