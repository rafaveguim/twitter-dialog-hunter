configs=(config_*.ini)

for config in "${configs[@]}"
do
  prefix=${config%.ini} # strip file extension
  #echo $prefix.out
  python getdialogs.py --min_length=6 --max_length=6 --config=$config --max_threads=5 --max_processes=4 ~/data/$prefix.out
done

