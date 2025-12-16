var gulp = require('gulp')
require('traceur/bin/traceur-runtime')
var $ = require('gulp-load-plugins')({
    lazy: true
});


gulp.task('default', ['serve-dev'])

gulp.task('test', ['build'], function () {
    return gulp.src('build/**/*Spec.js', {
            read: false
        })
        .pipe($.mocha({
            reporter: 'nyan'
        }))
})

gulp.task('serve-dev', ['build'], function () {
    serve(true)
})

gulp.task('serve-build', ['build'], function () {
    serve(false)
})

gulp.task('clean', function () {
    return gulp.src('build', {
            read: false
        })
        .pipe($.clean())
})

gulp.task('build', ['clean'], function () {
    gulp.src('src/views/**')
        .pipe(gulp.dest('build/views/'));

    return gulp.src('src/**/*.js')
        .pipe($.sourcemaps.init())
        .pipe($.traceur({annotations:true, types:true, typeAssertions:true, typeAssertionModule:'../assert'}))
        .pipe($.sourcemaps.write('.'))
        .pipe(gulp.dest('build'))
})

gulp.task('test', ['build'], function () {
    return gulp.src('build/**/*Spec.js', {
            read: false
        })
        .pipe($.mocha())
})

function serve(isDev) {
    require('./build')

    var debug = true //args.debug || args.debugBrk

    if (debug) {
        var exec = require('child_process').exec
        exec('node-inspector')
    }
}
