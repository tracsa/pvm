#!/bin/bash
fres=0

for f in `ls xml/*.xml`; do
    xmllint --noout --relaxng cacahuate/xml/process-spec.rng $f;
    res=$?

    if [ $res -ne 0 ]; then
        fres=$res
    fi
done

exit $fres
