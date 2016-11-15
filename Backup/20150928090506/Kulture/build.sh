#!/bin/bash
# Add K to path and trigger build
ver=`cat ~/.k/alias/default.alias`
add_to_path=$HOME"/.k/runtimes/"$ver"/bin"
export PATH=$PATH:/usr/local/bin:$add_to_path
[ -s $HOME"/.k/kvm/kvm.sh" ] && . $HOME"/.k/kvm/kvm.sh"
directory="./"
temp=$directory"project.json"
counter=0
# If unable to find project.json, keep going up a directory till project.json found
while [ ! -f $temp ]
do
	let counter=counter+1
	if [ $counter -gt 3 ]
	then
		break
	fi
	directory=$directory"../"
	temp=$directory"project.json"
done
kpm build $directory
