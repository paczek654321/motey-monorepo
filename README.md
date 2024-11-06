# Motey

## Showcase: [https://diode.zone/w/aXNYaER47MnTu8uw4LZSFW](https://diode.zone/w/aXNYaER47MnTu8uw4LZSFW)

## Setup

* Create .env file from template:
```shell
cp .env.dist .env
```
Replace default variables with your own

* Run the script:
```shell
./setup.sh
```

## Run

### Local/Testing:

* Source the script:
```shell
source run_local.sh
```

### Production:

* Change the domain in `Caddyfile`
* Run the script:
```shell
./run_prod.sh
```
