CC = g++ -std=c++11
JCC = gcc
UNAME_S := $(shell uname -s)

LOCAL_PREFIX = $(CURDIR)/.deps/local
DEPS_BUILD_DIR = $(CURDIR)/.deps/build
GF_SRC_DIR = $(DEPS_BUILD_DIR)/gf-complete
REDIS_SRC_DIR = $(DEPS_BUILD_DIR)/redis-3.2.8
GF_LIB = $(LOCAL_PREFIX)/lib/libgf_complete.a
HIREDIS_LIB = $(LOCAL_PREFIX)/lib/libhiredis.a

CPPFLAGS = -I$(LOCAL_PREFIX)/include
SYS_LIBS = -lm
ifeq ($(UNAME_S),Linux)
SYS_LIBS += -lrt
endif
CLIBS = -pthread $(GF_LIB) $(HIREDIS_LIB) $(SYS_LIBS)
#CFLAGS = -O3 -mmmx -msse -mpclmul -msse4.2 -DINTEL_SSE4 -mavx
CFLAGS = -g -Wall -O3

SRC_DIR =  src
UTIL_SRC_DIR = $(SRC_DIR)/Util

CC_FILES = $(filter-out $(SRC_DIR)/ECCoordinator.cc $(SRC_DIR)/ECHelper.cc $(SRC_DIR)/ECPipeClient.cc, \
			$(wildcard $(SRC_DIR)/*.cc))
UTIL_CC_FILES = $(wildcard $(UTIL_SRC_DIR)/*.cpp)
JERASURE_C_FILES = $(wildcard $(UTIL_SRC_DIR)/*.c)

OBJ_DIR = obj
OBJ_FILES = $(addprefix $(OBJ_DIR)/CC_, $(notdir $(CC_FILES:.cc=.o)))
UTIL_OBJ_FILES = $(addprefix $(OBJ_DIR)/UTIL_, $(notdir $(UTIL_CC_FILES:.cpp=.o)))
JERASURE_OBJ_FILES = $(addprefix $(OBJ_DIR)/J_, $(notdir $(JERASURE_C_FILES:.c=.o)))

O_FILES := $(OBJ_FILES) $(UTIL_OBJ_FILES) $(JERASURE_OBJ_FILES)

all : directories deps ECCoordinator ECHelper ECPipeClient

test : initRedisTest extractorTest initRedisCycTest PPRIdxTest

deps : $(GF_LIB) $(HIREDIS_LIB)

$(GF_SRC_DIR)/.unpacked :
	mkdir -p $(DEPS_BUILD_DIR)
	tar -xzf ins_pac/gf-complete.tar.gz -C $(DEPS_BUILD_DIR)
	touch $@

$(REDIS_SRC_DIR)/.unpacked :
	mkdir -p $(DEPS_BUILD_DIR)
	tar -xzf ins_pac/redis-3.2.8.tar.gz -C $(DEPS_BUILD_DIR)
	touch $@

$(GF_LIB) : $(GF_SRC_DIR)/.unpacked
	cd $(GF_SRC_DIR) && ./configure --prefix=$(LOCAL_PREFIX) --disable-neon
	$(MAKE) -C $(GF_SRC_DIR)
	$(MAKE) -C $(GF_SRC_DIR) install

$(HIREDIS_LIB) : $(REDIS_SRC_DIR)/.unpacked
	$(MAKE) -C $(REDIS_SRC_DIR)/deps/hiredis static
	mkdir -p $(LOCAL_PREFIX)/include/hiredis $(LOCAL_PREFIX)/lib
	cp $(REDIS_SRC_DIR)/deps/hiredis/hiredis.h $(LOCAL_PREFIX)/include/hiredis/
	cp $(REDIS_SRC_DIR)/deps/hiredis/async.h $(LOCAL_PREFIX)/include/hiredis/
	cp -R $(REDIS_SRC_DIR)/deps/hiredis/adapters $(LOCAL_PREFIX)/include/hiredis/
	cp $(REDIS_SRC_DIR)/deps/hiredis/libhiredis.a $(LOCAL_PREFIX)/lib/

directories : $(OBJ_DIR)

$(OBJ_DIR) : 
	mkdir -p $(OBJ_DIR)

ECCoordinator : $(SRC_DIR)/ECCoordinator.cc $(O_FILES)
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $^ $(CLIBS)

ECHelper : $(SRC_DIR)/ECHelper.cc $(O_FILES)
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $^ $(CLIBS)

ECPipeClient : $(SRC_DIR)/ECPipeClient.cc $(O_FILES)
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $^ $(CLIBS)

$(OBJ_DIR)/CC_%.o : $(SRC_DIR)/%.cc $(SRC_DIR)/%.hh | deps
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ -c $<

$(OBJ_DIR)/UTIL_%.o : $(UTIL_SRC_DIR)/%.cpp $(UTIL_SRC_DIR)/%.h | deps
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ -c $<

$(OBJ_DIR)/J_%.o : $(UTIL_SRC_DIR)/%.c $(UTIL_SRC_DIR)/%.h | deps
	$(JCC) $(CPPFLAGS) $(CFLAGS) -o $@ -c $<

%Test : src/test/%.cc
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $< $(CLIBS)

clean :
	rm -f ECCoordinator ECHelper ECPipeClient obj/*.o

distclean : clean
	rm -rf $(CURDIR)/.deps
