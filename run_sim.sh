if [ $3 -eq 1 ]
then
make -j8 -C ../../src/enzo/
fi
cp ../../src/enzo/enzo.exe ./
rm -r $2/$1; mkdir $2/$1
cp -rv $1 $2
cp -rv ./enzo.exe $2/$1
CURRENT=$(pwd)
cd $2/$1
echo changing directory
pwd
start=`date +%s`
mpirun -np 8 ./enzo.exe -d $1.enzo |& tee output.txt
end=`date +%s`
runtime=$((end-start))
echo runtime $runtime |& tee -a output.txt
cd $CURRENT
echo changing directory back
pwd
grep NumberOfParticles $2/$1/Data/DD????/DD???? |& tee -a output.txt