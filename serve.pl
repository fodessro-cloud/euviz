use strict;
use IO::Socket::INET;
use Cwd 'abs_path';
use File::Basename;

my $root = dirname(abs_path($0));
my $port = 3141;

my %TYPES = (
    html => 'text/html; charset=utf-8',
    css  => 'text/css',
    js   => 'application/javascript',
    png  => 'image/png',
    jpg  => 'image/jpeg',
    svg  => 'image/svg+xml',
    ico  => 'image/x-icon',
);

my $server = IO::Socket::INET->new(
    LocalPort => $port,
    Listen    => 20,
    ReuseAddr => 1,
    Proto     => 'tcp',
) or die "Cannot bind $port: $!";

print "EUViz at http://localhost:$port\n";
$| = 1;

while (my $client = $server->accept) {
    eval {
        my $req = '';
        while (my $line = <$client>) {
            $req .= $line;
            last if $line =~ /^\r?\n$/;
        }

        my ($path) = ($req =~ /^GET\s+(\S+)/);
        $path //= '/';
        $path =~ s/\?.*//;
        $path =~ s/%([0-9A-Fa-f]{2})/chr(hex($1))/eg;
        $path =~ s|[^/a-zA-Z0-9._-]||g;

        my $file = $root . $path;
        $file .= 'index.html' if $path =~ m|/$|;

        if (-f $file) {
            my ($ext) = ($file =~ /\.([^.]+)$/);
            my $ct = $TYPES{lc($ext) // ''} // 'application/octet-stream';
            open my $fh, '<:raw', $file or die "open: $!";
            local $/; my $body = <$fh>; close $fh;
            print $client "HTTP/1.1 200 OK\r\nContent-Type: $ct\r\n"
                        . "Content-Length: " . length($body) . "\r\n\r\n$body";
        } else {
            my $msg = "404 - Not found: $path";
            print $client "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n"
                        . "Content-Length: " . length($msg) . "\r\n\r\n$msg";
        }
    };
    close $client;
}
