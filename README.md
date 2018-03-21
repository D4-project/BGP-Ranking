# BGP-Ranking
New version of BGP Ranking, complete rewrite in python3.6+ and an ARDB backend

# Directory structure

*Config files*: `listimport / modules_config / *.json`

*Per-module parsers*: `listimport / parsers`

*Libraries* : `listimport / libs`

# Raw dataset directory structure

## Files to import

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
