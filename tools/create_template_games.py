"""Generate the two editable native game projects without deleting their folders."""
from pathlib import Path
import argparse
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def launchers(root):
    for name in ('Play','Replay'):
        (root/(name+'.cmd')).write_text('@echo off\nif not exist "%~dp0dist\\'+name+'.cmd" (\n'
            '  echo Build and package this .nen project with Node_Engine first.\n  exit /b 1\n)\n'
            'call "%~dp0dist\\'+name+'.cmd" %*\n',encoding='ascii')


def flappy(root):
    from tools.create_flappy_bird_template import create
    root=Path(root);result=create(root);launchers(root);return result


def snake(root):
    from tools.create_isometric_snake_template import create
    root=Path(root);result=create(root);launchers(root);return result


def create(output):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    flappy(output/'flappy_bird')
    snake(output/'isometric_snake_3d')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'templates/games')
    print(create(parser.parse_args().output))
