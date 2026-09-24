"""Run the existing Set-A instruments in new replacement-Seed directories."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
kind=sys.argv.pop(1)
names={'price':'seed_price','media':'seed_media','group':'native_group',
       'currency':'currency','currency-proof':'currency_proof','ledger':'ledger',
       'prerequisites':'prerequisite_native','capacity':'capacity_native','order':'order'}
assert kind in names
source=ROOT/f'tools/host-lisp/definition_set_a_{names[kind]}.py'
raw=source.read_text()
replacements={
    'import definition_set_a_producer as DRIVER':'import definition_set_a_auth_producer as DRIVER',
    'build/definition-set-a-product-r1/':'build/definition-set-a-product-r2/',
    'build/definition-set-a-product-r2-preflight':'build/definition-set-a-product-r3-preflight',
    'build/definition-set-a-seed-medium-r1':'build/definition-set-a-seed-medium-r2',
    'build/definition-set-a-r2':'build/definition-set-a-r3',
    'build/definition-set-a-native-group-':'build/definition-set-a-auth-native-group-',
    'build/definition-set-a-five-ide-':'build/definition-set-a-auth-five-ide-',
    'build/definition-set-a-ledger-':'build/definition-set-a-auth-ledger-',
    'build/definition-set-a-prerequisites-r1':'build/definition-set-a-auth-prerequisites-r1',
    'build/definition-set-a-capacity-':'build/definition-set-a-auth-capacity-',
    'build/definition-set-a-order-r1':'build/definition-set-a-auth-order-r1',
}
for old,new in replacements.items():raw=raw.replace(old,new)
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
