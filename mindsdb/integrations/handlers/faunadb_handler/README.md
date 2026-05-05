# FaunaDB Handler

This is the implementation of the FaunaDB for MindsDB.

## FaunaDB

FaunaDB is a distributed document-relational database delivered as a cloud API. Fauna is a fast, reliable, consistent relational database.

## Implementation

This handler uses `faunadb` python library connect to a faunadb instance.

The required arguments to establish a connection are:

* `fauna_secret`: the secret key for connecting to a faunadb instance
either
* `fauna_endpoint`: the port to use when connecting
or
* `fauna_scheme`: the protocol used in the faunadb's instance
* `fauna_domain`: the domain on which the instance is hosted
* `fauna_port`: the port on which the instance is listening


## Usage

In order to make use of this handler and connect to a hosted FaunaDB instance in Cloud, the following syntax can be used:

```sql
CREATE DATABASE fauna_dev
WITH ENGINE = 'faunadb',
PARAMETERS = {
  "fauna_secret": "kdvozJsm9LhYkCYtH2VbX55AUFQFQPZNAA",
  "fauna_endpoint": "https://db.fauna.com:443"
};
```

Another option is to use separate config fields like scheme(protocol), the domain and the port of the instance of the faunadb database:

```sql
CREATE DATABASE fauna_dev
WITH ENGINE = "faunadb",
PARAMETERS = {
    "fauna_secret": "kdvozJsm9LhYkCYtH2VbX55AUFQFQPZNAA",
    "fauna_scheme": "https",
    "fauna_domain": "db.fauna.com",
    "fauna_port": 443
}
```

You can insert data into a new collection like so:

```sql
CREATE TABLE fauna_dev.books
    (SELECT * FROM other.source);
```

You can query a collection within your FaunaDB instance as follows:

```sql
SELECT * FROM fauna_dev.books;
```

You can insert into a collection i.e. create documents in faunadb as follows:

```sql
INSERT INTO fauna_dev.books (name, author)
VALUES
    ("The Hobbit", "J.R.R Tolkein"),
    ("Good Omens", "Neil Gaiman");
```
OR
dump as a json data

```sql
INSERT INTO fauna_dev.books (data)
VALUES (
    '[
      {"name": "The Hobbit", "author": "J.R.R. Tolkein"},
      {"name": "Good Omens", "author": "Neil Gaiman"}
    ]'
);
```
