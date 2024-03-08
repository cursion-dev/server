import yellowLabTools from "yellowlabtools"

function main(args){
    var yltOptions = {
        device: args.device,
    };
    yellowLabTools(args.url, yltOptions)
        .then(function(data) {
            return data
        })
        .fail(function(err) {
            return err
        });
}

export default main
