# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file for more information.

export JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64"
export HDFS_NAMENODE_USER=cord
export HDFS_DATANODE_USER=cord
export HDFS_SECONDARYNAMENODE_USER=cord

export HADOOP_OS_TYPE=${HADOOP_OS_TYPE:-$(uname -s)}
