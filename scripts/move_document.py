import shutil, os
src = os.path.join('backend','documents','2026','02','02','714_Amended_directive_for_the_registration_of_construction_professi_kuGqbaa.pdf')
dst_dir = os.path.join('backend','media','documents','2026','02','02')
if not os.path.exists(src):
    print('SRC_NOT_FOUND')
else:
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    print('COPIED', dst)
