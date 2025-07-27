{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  nativeBuildInputs = with pkgs; [ libudev-zero libudev0-shim linuxHeaders ];
  C_INCLUDE_PATH = "${pkgs.linuxHeaders}/include";
}

