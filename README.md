# Get it running

```
cp .env.example .env
docker build -t my-proof .
docker run --rm --net=host --volume ./input:/input --volume ./output:/output --env-file .env my-proof
```

# Description

The validator is set up to check audio files against the following four parameters:

* **Authenticity**: Ensures that the data is real and unaltered.
* **Ownership**: Confirms the data belongs to the contributor.
* **Quality**: Measures the relevance and utility of the data.
* **Uniqueness**: Prevents redundant or copied data from being reused.

See below for the technologies used to build each parameter:

### Authenticity

Authenticity verifies whether audio was produced by a human. We use our custom AI model to check this. In the future, we will continue to modify this parameter to address the growing challenge of detecting increasingly sophisticated generated speech.

### Ownership

Ownership is verified using a trust-based approach. Users are assumed to own the data they submit unless they fail authenticity checks repeatedly. If more than 10 audio submissions fail verification, the user is banned from contributing.

### Quality

To assess audio quality we use the P.835 evaluation [(read about it here](https://arxiv.org/abs/2110.01763)), which involves analyzing three parameters: (1) speech quality, (2) the level and presence of noise, and (3) the inherent quality of the audio recording itself.

### Uniqueness

Uniqueness is verified the next way: we compute an audio fingerprint and compare it against existing entries using the [acoustid](https://pypi.org/project/pyacoustid/) library. Passing both checks confirms the audio is unique.
