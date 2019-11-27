# BGP Ranking

For an Internet Service Provider, AS numbers are a logical representation of
the other ISP peering or communicating with its autonomous system. ISP customers
are using the capacity of the Internet Service Provider to reach Internet
services over other AS. Some of those communications can be malicious (e.g. due
to malware activities on an end-user equipments) and hosted at specific AS location.

In order to provide an improved security view on those AS numbers, a trust ranking
scheme is implemented based on existing dataset of compromised systems,
malware C&C IP and existing datasets. BGP Ranking provides a way to collect
such malicious activities, aggregate the information per ASN and provide a ranking
model to rank the ASN from the most malicious to the less malicious ASN.

The official website of the project is: [https://github.com/D4-project/bgp-ranking/](https://github.com/D4-project/bgp-ranking/)

There is a public BGP Ranking at [http://bgpranking.circl.lu/](http://bgpranking.circl.lu/)

BGP Ranking is free software licensed under the GNU Affero General Public License

BGP Ranking is a software to rank AS numbers based on their malicious activities.

# Python client

```bash
$ pip install git+https://github.com/D4-project/BGP-Ranking.git/#egg=pybgpranking\&subdirectory=client
$ bgpranking --help
usage: bgpranking [-h] [--url URL] (--asn ASN | --ip IP)

Run a query against BGP Ranking

optional arguments:
  -h, --help  show this help message and exit
  --url URL   URL of the instance.
  --asn ASN   ASN to lookup
  --ip IP     IP to lookup
```

## History

The first version of BGP Ranking was done in 2010 by [Raphael Vinot](https://github.com/Rafiot) with the support of [Alexandre Dulaunoy](https://github.com/adulau/).
CIRCL supported the project from the early beginning and setup an online version to share information about the malicious ranking of ISPs.

In late 2018 within the scope of the D4 Project (a CIRCL project co-funded by INEA under the CEF Telecom program), a new version of BGP Ranking was completed rewritten in python3.6+ with an ARDB back-end.

# Online service

BGP Ranking service is available online [http://bgpranking.circl.lu/](http://bgpranking.circl.lu/).

A Python library and client software is [available](https://github.com/D4-project/BGP-Ranking/tree/master/client) using the default API available from bgpranking.circl.lu.

# CURL Example

## Get the ASN from an IP or a prefix
```bash
curl https://bgpranking-ng.circl.lu/ipasn_history/?ip=143.255.153.0/24
```

## Response

```json
{
  "meta": {
    "address_family": "v4",
    "ip": "143.255.153.0/24",
    "source": "caida"
  },
  "response": {
    "2019-05-19T12:00:00": {
      "asn": "264643",
      "prefix": "143.255.153.0/24"
    }
  }
}
```

## Get the ranking of the AS
```
curl -X POST -d '{"asn": "5577", "date": "2019-05-19"}' https://bgpranking-ng.circl.lu/json/asn
```

Note: `date` isn't required.

### Response

```json
{
  "meta": {
    "asn": "5577"
  },
  "response": {
    "asn_description": "ROOT, LU",
    "ranking": {
      "rank": 0.0004720052083333333,
      "position": 7084,
      "total_known_asns": 15375
    }
  }
}
```

## Get historical information for an ASN

```
curl -X POST -d '{"asn": "5577", "period": 5}' https://bgpranking-ng.circl.lu/json/asn_history
```

### Response

```json
{
  "meta": {
    "asn": "5577",
    "period": 5
  },
  "response": {
    "asn_history": [
      [
        "2019-11-10",
        0.00036458333333333335
      ],
      [
        "2019-11-11",
        0.00036168981481481485
      ],
      [
        "2019-11-12",
        0.0003761574074074074
      ],
      [
        "2019-11-13",
        0.0003530092592592593
      ],
      [
        "2019-11-14",
        0.0003559027777777778
      ]
    ]
  }
}
```


# Server Installation (if you want to run your own)

**IMPORTANT**: Use [pipenv](https://pipenv.readthedocs.io/en/latest/)

**NOTE**: Yes, it requires python3.6+. No, it will never support anything older.

## Install redis

```bash
git clone https://github.com/antirez/redis.git
cd redis
git checkout 5.0
make
make test
cd ..
```

## Install ardb

```bash
git clone https://github.com/yinqiwen/ardb.git
cd ardb
DISABLE_WARNING_AS_ERROR=1 make  # ardb (more precisely rocksdb) doesn't compile on ubuntu 18.04 unless you disable warning as error
cd ..
```

## Install & run BGP Ranking

```bash
git clone https://github.com/D4-project/BGP-Ranking.git
cd BGP-Ranking
pipenv install
echo BGPRANKING_HOME="'`pwd`'" > .env
pipenv shell
# Starts all the backend
start.py
# Start the web interface
start_website.py
```

## Shutdown BGP Ranking

```bash
stop.py
```

# Directory structure

*Config files*: `bgpranking / config / *.json`

*Per-module parsers*: `bgpraking / parsers`

*Libraries* : `brpranking / libs`

# Raw dataset directory structure

## Files to import

*Note*: The default location of `<storage_directory>` is the root directory of the repo.

`<storage_directory> / <vendor> / <listname>`

## Last modified date (if possible) and lock file

`<storage_directory> / <vendor> / <listname> / meta`

## Imported files less than 2 months old

`<storage_directory> / <vendor> / <listname> / archive`

## Imported files more than 2 months old

`<storage_directory> / <vendor> / <listname> / archive / deep`

# Databases

## Intake (redis, port 6579)

*Usage*: All the modules push their entries in this database.

Creates the following hashes:

```python
UUID = {'ip': <ip>, 'source': <source>, 'datetime': <datetime>}
```

Creates a set `intake` for further processing containing all the UUIDs.


## Pre-Insert (redis, port 6580)


*Usage*: Make sure th IPs are global, validate input from the intake module.

Pop UUIDs from `intake`, get the hashes with that key

Creates the following hashes:

```python
UUID = {'ip': <ip>, 'source': <source>, 'datetime': <datetime>, 'date': <date>}
```

Creates a set `to_insert` for further processing containing all the UUIDs.

Creates a set `for_ris_lookup` to lookup on the RIS database. Contains all the IPs.

## Routing Information Service cache (redis, port 6581)

*Usage*: Lookup IPs against the RIPE's RIS database

Pop IPs from `for_ris_lookup`.

Creates the following hashes:

```python
IP = {'asn': <asn>, 'prefix': <prefix>, 'description': <description>}
```

## Ranking Information cache (redis, port 6582)

*Usage*: Store the current list of known ASNs at RIPE, and the prefixes originating from them.

Creates the following sets:

```python
asns = set([<asn>, ...])
<asn>|v4 = set([<ipv4_prefix>, ...])
<asn>|v6 = set([<ipv6_prefix>, ...])
```

And the following keys:

```python
<asn>|v4|ipcount = <Total amount of IP v4 addresses originating this AS>
<asn>|v6|ipcount = <Total amount of IP v6 addresses originating this AS>
```

## Long term storage (ardb, port 16579)

*Usage*: Stores the IPs with the required meta informations required for ranking.

Pop UUIDs from `to_insert`, get the hashes with that key

Use the IP from that hash to get the RIS informations.

Creates the following sets:

```python
# All the sources, by day
<YYYY-MM-DD>|sources = set([<source>, ...])
# All the ASNs by source, by day
<YYYY-MM-DD>|<source> -> set([<asn>, ...])
# All the prefixes, by ASN, by source, by day
<YYYY-MM-DD>|<source>|<asn> -> set([<prefix>, ...])
# All the tuples (ip, datetime), by prefixes, by ASN, by source, by day
<YYYY-MM-DD>|<source>|<asn>|<prefix> -> set([<ip>|<datetime>, ...])
```
