if [[ -z $1 || -z $2 ]]; then
    echo "Usage: vbump (major|minor|patch) <msg>"
    return 1
fi

file=cacahuate/version.txt
segment=$2
msg=$3

old_ver=`cat $file`

if [[ -z $old_ver ]]; then
    echo "empty version file"
    return 2
fi

version=`python ~/.local/bump.py $old_ver $segment`

if [[ -z $version ]]; then
    echo "python script failed"
    return 3
fi

echo $version > $file

git add $file
git commit -m "v$version $msg"
git tag v$version
