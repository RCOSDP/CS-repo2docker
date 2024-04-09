# MATLAB (mpm)の設定 / Configuration of MATLAB (mpm)

MATLAB (mpm) では、インストールしたい環境やアドオンを自由に指定することができます。以下の項目が設定可能です。

In MATLAB (mpm), you can freely specify the environment and addons you want to install. The following items can be configured.

# リリース / Release

リリースには、インストールしたいMATLABのバージョンを指定することができます。以下の、MATLAB Dependenciesに記載のバージョンのうち OS Ubuntu 22.04 に対応したバージョンを使用することができます。

For the Release, you can specify the version of MATLAB you want to install. You can use a version that is compatible with OS Ubuntu 22.04, as listed in the MATLAB Dependencies below.

https://github.com/mathworks-ref-arch/container-images/tree/main/matlab-deps

# アドオン / Add-ons

アドオンには、インストールしたいMATLABの機能拡張(アドオン)を指定することができます。以下の、mpm-input-filesに記載のアドオン名を指定することができます。

For the Add-ons, you can specify the extensions (add-ons) of MATLAB you want to install. You can specify the add-on names listed in mpm-input-files below.

https://github.com/mathworks-ref-arch/matlab-dockerfile/tree/main/mpm-input-files

指定可能なアドオン名を確認するためには、使用したいリリースのmpm-input-filesのうち、指定可能なバージョン番号を持つmpm_input_(release).txt を参照してください。

例えば R2023b ならば、 https://github.com/mathworks-ref-arch/matlab-dockerfile/blob/main/mpm-input-files/R2023b/mpm_input_r2023b.txt を参照してください。このファイルの各行のうち、 #product. で示される行が指定可能なアドオン名を示しています。

For example, if you are using R2023b, please refer to https://github.com/mathworks-ref-arch/matlab-dockerfile/blob/main/mpm-input-files/R2023b/mpm_input_r2023b.txt. The lines in this file that are indicated with #product. represent the add-on names that can be specified.

```
#product.Simulink
```

「Simulink」をアドオンに指定可能であることを示します。

You can specify "Simulink" as an add-on.